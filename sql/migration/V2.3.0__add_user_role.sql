-- Admin backend role support.

ALTER TABLE `user`
    ADD COLUMN `role` VARCHAR(20) NOT NULL DEFAULT 'USER' COMMENT 'USER/ADMIN' AFTER `enabled`;

UPDATE `user`
SET `role` = 'ADMIN'
WHERE LOWER(`username`) = 'admin';

ALTER TABLE `user`
    ADD INDEX `idx_role` (`role`);
