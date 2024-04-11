EXTENSION = dbfarmer
VRESION = 1.0
MODULE_big = dbfarmer

PG_CONFIG = pg_config
PG_CPPFLAGS = -I$(libpq_srcdir)
SHLIB_LINK_INTERNAL = $(libpq)

FILES = $(shell find . -type f -name "*.c")
OBJS = $(foreach FILE,$(FILES),$(subst .c,.o,$(FILE)))

PGXS := $(shell $(PG_CONFIG) --pgxs)
include $(PGXS)
