"""
Database Connection Pool Module
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Provides thread-safe MySQL 8.0+ connection pooling using mysql-connector or PyMySQL.
"""

import os
import logging
from contextlib import contextmanager
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    root_dir = Path(__file__).resolve().parent.parent
    env_file = root_dir / '.env'
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
    else:
        load_dotenv(dotenv_path=root_dir / '.env.example')
except ImportError:
    pass

logger = logging.getLogger("db_pool")

class DatabasePoolManager:
    """Singleton connection pool manager for MySQL InnoDB engine."""
    _instance = None
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabasePoolManager, cls).__new__(cls)
            cls._instance._init_pool()
        return cls._instance

    def _init_pool(self):
        host = os.getenv("DB_HOST", "127.0.0.1")
        port = int(os.getenv("DB_PORT", "3306"))
        user = os.getenv("DB_USER", "root")
        password = os.getenv("DB_PASSWORD", "")
        db_name = os.getenv("DB_NAME", "smart_poll_allocation_db")
        pool_size = int(os.getenv("DB_POOL_SIZE", "10"))

        try:
            from mysql.connector import pooling
            self._pool = pooling.MySQLConnectionPool(
                pool_name="smart_poll_pool",
                pool_size=pool_size,
                pool_reset_session=True,
                host=host,
                port=port,
                user=user,
                password=password,
                database=db_name,
                autocommit=False
            )
            logger.info("Initialized MySQLConnectionPool with %d connections.", pool_size)
            self._driver = "mysql-connector"
        except ImportError:
            logger.warning("mysql-connector-python not found. Falling back to dynamic PyMySQL connections.")
            self._driver = "pymysql"
            self._config = {
                "host": host,
                "port": port,
                "user": user,
                "password": password,
                "database": db_name,
                "autocommit": False
            }

    @contextmanager
    def get_connection(self):
        """Context manager yielding a database connection from the pool."""
        conn = None
        try:
            if self._driver == "mysql-connector":
                conn = self._pool.get_connection()
            else:
                import pymysql
                conn = pymysql.connect(**self._config)
            yield conn
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    logger.error("Error closing connection: %s", e)

    @contextmanager
    def get_cursor(self, dictionary=True):
        """Context manager yielding (connection, cursor) with dictionary output option."""
        with self.get_connection() as conn:
            if self._driver == "mysql-connector":
                cursor = conn.cursor(dictionary=dictionary)
            else:
                import pymysql
                cursor = conn.cursor(pymysql.cursors.DictCursor if dictionary else None)
            try:
                yield conn, cursor
            finally:
                cursor.close()

# Global accessor
db_pool = DatabasePoolManager()
