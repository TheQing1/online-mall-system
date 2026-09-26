-- 只负责建库。表结构由 Alembic 迁移创建，不要在此手工建表，
-- 否则会和 `alembic upgrade head` 的幂等判断打架。
--
-- 运行方式: mysql -u root -p < docs/init.sql
--   然后:   cd backend && alembic upgrade head && python -m app.core.seed

CREATE DATABASE IF NOT EXISTS online_mall
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE online_mall;
