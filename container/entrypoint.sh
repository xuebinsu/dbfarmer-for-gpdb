#!/bin/bash

set -o errexit -o nounset -o pipefail -o xtrace

# shellcheck source=/dev/null
source "$HOME"/.profile
ls -lh "$HOME"

exec_sql() {
    export PGOPTIONS='-c gp_role=utility'
    pg_ctl -o "$PGOPTIONS" start
    psql postgres -c "$1"
    pg_ctl stop
}

if [[ ! -f $PGDATA/PG_VERSION ]]; then
    initdb -D "$PGDATA"
    INIT_CONF="
        # for cluster management
        gp_dbid = ${CLUSTER_DBID}
        gp_contentid = ${CLUSTER_CONTENTID}

        log_statement = 'all'
        log_connections = on
        log_disconnections = on
        listen_addresses = '*'
        shared_preload_libraries = dbfarmer
    "
    echo "$INIT_CONF" >>"$PGDATA/postgresql.conf"
    cat "$PGDATA/postgresql.conf"
    echo "local all $(whoami) trust" >"$PGDATA"/pg_hba.conf
    if [[ $CLUSTER_CONTENTID == -1 ]]; then
        INIT_SQL="
        DO \$\$ BEGIN 
            SET LOCAL allow_system_table_mods TO TRUE; 
            INSERT INTO gp_segment_configuration 
            SELECT 
                dbid, 
                dbid - 2 AS content, 
                'p' AS role, 
                'p' AS preferred_role, 
                'n' AS mode, 
                'u' AS status, 
                0 AS port, 
                '' AS hostname, 
                '' AS address, 
                '' AS datadir 
            FROM generate_series(1, ${CLUSTER_NUM_SEGMENTS} + 1) AS dbid;
        END \$\$;
        "
        exec_sql "$INIT_SQL"
    fi
    echo "host all $(whoami) samenet trust" >>"$PGDATA"/pg_hba.conf
    cat "$PGDATA"/pg_hba.conf
fi

if [[ $CLUSTER_CONTENTID == -1 ]]; then
    START_SQL="
        DO \$\$ BEGIN 
        SET LOCAL allow_system_table_mods TO TRUE; 
        UPDATE gp_segment_configuration SET
            port = ${PGPORT},
            hostname = '${CLUSTER_COORDINATOR_HOST}',
            address = '${CLUSTER_COORDINATOR_HOST}'
        WHERE content = -1;
        END \$\$;
    "
    exec_sql "$START_SQL"
    exec postgres \
        -c gp_role=dispatch \
        -c port="${PGPORT}"
else
    exec postgres \
        -c gp_role=execute \
        -c port="${PGPORT}" \
        -c dbfarmer.coordinator_host="${CLUSTER_COORDINATOR_HOST}" \
        -c dbfarmer.coordinator_port="${CLUSTER_COORDINATOR_PORT}"
fi
