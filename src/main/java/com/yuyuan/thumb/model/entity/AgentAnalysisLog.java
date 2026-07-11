package com.yuyuan.thumb.model.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.util.Date;

@Data
@TableName("agent_analysis_log")
public class AgentAnalysisLog {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String question;

    private String intent;

    @TableField("user_id")
    private Long userId;

    private String role;

    @TableField("sql_text")
    private String sqlText;

    private String status;

    @TableField("row_count")
    private Integer rowCount;

    private Double confidence;

    @TableField("chart_json")
    private String chartJson;

    @TableField("result_json")
    private String resultJson;

    private String insight;

    @TableField("suggestions_json")
    private String suggestionsJson;

    @TableField("plan_json")
    private String planJson;

    @TableField("error_message")
    private String errorMessage;

    @TableField("created_at")
    private Date createdAt;
}
