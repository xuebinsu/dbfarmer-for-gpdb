/* clang-format off */
#include "postgres.h"
/* clang-format on */

#include <arpa/inet.h>
#include <sys/param.h>
#include <unistd.h>

#include "access/genam.h"
#include "access/table.h"
#include "access/xact.h"
#include "catalog/indexing.h"
#include "cdb/cdbvars.h"
#include "common/ip.h"
#include "executor/spi.h"
#include "fmgr.h"
#include "lib/ilist.h"
#include "libpq-fe.h"
#include "libpq/ifaddr.h"
#include "miscadmin.h"
#include "postmaster/bgworker.h"
#include "postmaster/bgworker_internals.h"
#include "postmaster/postmaster.h"
#include "utils/builtins.h"
#include "utils/fmgroids.h"
#include "utils/guc.h"
#include "utils/rel.h"

PG_MODULE_MAGIC;

/* GUCs */
static char *coordinator_host = NULL;
static int coordinator_port = 0;

#define MAX_PORT_STR_LENGTH 5 + 1 /* <= 65535 */

extern void report_segment_status(Datum);

void report_segment_status(Datum) {
  PGconn *conn = NULL;
  char coordinator_port_str[MAX_PORT_STR_LENGTH] = {'\0'};
  pg_snprintf(coordinator_port_str, MAX_PORT_STR_LENGTH, "%d",
              coordinator_port);
  /* Repeat until coordinator is up */
  for (;;) {
    conn = PQsetdb(coordinator_host, coordinator_port_str,
                   "-c gp_role=utility -c allow_system_table_mods=true", NULL,
                   "postgres");
    if (PQstatus(conn) == CONNECTION_OK) break;
    char *msg = pstrdup(PQerrorMessage(conn));
    ereport(LOG,
            (errcode(ERRCODE_SQLCLIENT_UNABLE_TO_ESTABLISH_SQLCONNECTION),
             errmsg("dbfarmer: Error connecting to coordinator at \"%s:%d\"",
                    coordinator_host, coordinator_port),
             errdetail_internal("%s", msg)));
    pfree(msg);
    PQfinish(conn);
  }
  char *sql =
      "UPDATE gp_segment_configuration SET "
      "dbid = %d, "
      "hostname = host(inet_client_addr()), "
      "address = host(inet_client_addr()), "
      "port = %d "
      "WHERE content = %d "
      "RETURNING *; ";
  StringInfoData buf;
  initStringInfo(&buf);
  appendStringInfo(&buf, sql, GpIdentity.dbid, PostPortNumber,
                   GpIdentity.segindex);
  /*
   * Coordinator should not accept any non-local connection before it is fully
   * initialized.
   */
  for (;;) {
    PGresult *res = PQexec(conn, buf.data);
    if (PQresultStatus(res) == PGRES_TUPLES_OK && PQntuples(res) == 1) {
      free(res);
      break;
    }
    char *msg = NULL;
    if (PQntuples(res) == 0) {
      msg = "dbfarmer: Segment config has not been initialized yet";
    } else if (PQntuples(res) > 1) {
      msg = "dbfarmer: Segment config is duplicated";
    } else {
      msg = "dbfarmer: Error reporting segment status to coordinator";
    }
    char *detail = pstrdup(PQresultErrorMessage(res));
    ereport(PANIC, (errcode(ERRCODE_INTERNAL_ERROR), errmsg("%s", msg),
                    errdetail("%s", detail)));
  }
  PQfinish(conn);
  elog(LOG, "dbfarmer: Successfully reported segment status. Exiting...");
}

static void remove_ftsprobe(void) {
  slist_mutable_iter iter;
  slist_foreach_modify(iter, &BackgroundWorkerList) {
    RegisteredBgWorker *rw =
        slist_container(RegisteredBgWorker, rw_lnode, iter.cur);
    if (strncmp(rw->rw_worker.bgw_name, "FtsProbeMain", BGW_MAXLEN)) {
      slist_delete_current(&iter);
      free(rw);
      return;
    }
  }
}

static void define_gucs(void) {
  DefineCustomStringVariable(
      "dbfarmer.coordinator_host", "Coordinator host to connect with libpq",
      NULL, &coordinator_host, NULL, PGC_POSTMASTER, 0, NULL, NULL, NULL);

  DefineCustomIntVariable("dbfarmer.coordinator_port",
                          "Coordinator port to connect with libpq", NULL,
                          &coordinator_port, 0, 1, 65535, PGC_POSTMASTER, 0,
                          NULL, NULL, NULL);
}

extern void _PG_init(void);

void _PG_init(void) {
  if (!process_shared_preload_libraries_in_progress) return;

  define_gucs();

  if (Gp_role == GP_ROLE_DISPATCH) {
    remove_ftsprobe();
    return;
  }

  if (Gp_role != GP_ROLE_EXECUTE) return;

  BackgroundWorker worker = {0};
  worker.bgw_restart_time = BGW_NEVER_RESTART;
  StrNCpy(worker.bgw_library_name, "dbfarmer", BGW_MAXLEN);
  char *bgw_name = NULL;

  StrNCpy(worker.bgw_function_name, "report_segment_status", BGW_MAXLEN);
  bgw_name = "dbfarmer reporter";
  worker.bgw_start_time = BgWorkerStart_ConsistentState;

  StrNCpy(worker.bgw_name, bgw_name, BGW_MAXLEN);
  StrNCpy(worker.bgw_type, bgw_name, BGW_MAXLEN);
  RegisterBackgroundWorker(&worker);
}
