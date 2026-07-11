package com.yuyuan.thumb.model.vo;

import lombok.Data;

import java.util.Date;
import java.util.List;

/**
 * 评论视图对象
 */
@Data
public class CommentVo {
    private Long id;
    private String content;
    private Date createdAt;
    private Long userId;
    private String username;
    private Long parentId;
    /** 情感得分（Agent 分析，范围 -100~100） */
    private Integer sentimentScore;
    /** 是否被标记违规（0-正常，1-标记违规） */
    private Integer isFlagged;
    private List<CommentVo> children;
}
