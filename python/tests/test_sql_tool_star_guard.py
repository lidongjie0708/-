import unittest

from app.tools import sql_tool


class StarGuardTests(unittest.TestCase):
    def test_select_star_is_rejected(self) -> None:
        ok, reason = sql_tool.validate_readonly_sql("SELECT * FROM blog LIMIT 10")
        self.assertFalse(ok)
        self.assertIn("SELECT *", reason)

    def test_comma_star_is_rejected(self) -> None:
        ok, reason = sql_tool.validate_readonly_sql("SELECT id, * FROM blog LIMIT 10")
        self.assertFalse(ok)
        self.assertIn("SELECT *", reason)

    def test_count_star_arithmetic_is_allowed(self) -> None:
        sql = (
            "SELECT COUNT(*) * 100.0 / (SELECT COUNT(*) FROM blog WHERE createTime >= DATE_SUB(NOW(), INTERVAL 30 DAY)) "
            "AS high_activity_ratio FROM blog b LEFT JOIN "
            "(SELECT blog_id, COUNT(*) AS comment_count FROM comments WHERE is_deleted = 0 AND is_flagged = 0 GROUP BY blog_id) c "
            "ON b.id = c.blog_id WHERE b.createTime >= DATE_SUB(NOW(), INTERVAL 30 DAY) "
            "AND b.thumbCount >= 10 AND COALESCE(c.comment_count, 0) >= 5 LIMIT 100"
        )
        ok, reason = sql_tool.validate_readonly_sql(sql)
        self.assertTrue(ok, reason)

    def test_plain_count_star_is_allowed(self) -> None:
        ok, reason = sql_tool.validate_readonly_sql("SELECT COUNT(*) AS total FROM blog LIMIT 1")
        self.assertTrue(ok, reason)


if __name__ == "__main__":
    unittest.main()
