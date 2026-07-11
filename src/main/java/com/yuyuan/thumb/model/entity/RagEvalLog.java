package com.yuyuan.thumb.model.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.util.Date;

@Data
@TableName("rag_eval_log")
public class RagEvalLog {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String question;

    private String answer;

    @TableField("user_id")
    private Long userId;

    private String role;

    private Double confidence;

    @TableField("citation_count")
    private Integer citationCount;

    @TableField("context_precision_lite")
    private Double contextPrecisionLite;

    @TableField("answer_grounding_lite")
    private Double answerGroundingLite;

    @TableField("has_citations")
    private Integer hasCitations;

    @TableField("keyword_hit_rate")
    private Double keywordHitRate;

    @TableField("query_rewrite_json")
    private String queryRewriteJson;

    @TableField("citations_json")
    private String citationsJson;

    @TableField("evaluation_json")
    private String evaluationJson;

    @TableField("created_at")
    private Date createdAt;
}
