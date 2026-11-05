"""Project package.

cPanel shared hosts often cannot compile ``mysqlclient``. PyMySQL is a
pure-Python drop-in, and ``install_as_MySQLdb()`` lets Django's MySQL backend
import it unchanged. The import is optional so SQLite development and hosts
that do use mysqlclient keep working.
"""
try:
    import pymysql
except ImportError:  # pragma: no cover - exercised only when the driver is absent
    pass
else:
    pymysql.install_as_MySQLdb()
