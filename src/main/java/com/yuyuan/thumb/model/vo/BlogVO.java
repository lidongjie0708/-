package com.yuyuan.thumb.model.vo;

import lombok.Data;

import java.util.Date;

/**
 * 
 * @TableName blog
 */
@Data
public class BlogVO {
    /**
     * 
     */
    private Long id;

    /**
     * 标题
     */
    private String title;

    /**
     * 封面
     */
    private String coverImg;

    /**
     * 内容
     */
    private String content;

    private String contentFormat;

    /**
     * 点赞数
     */
    private Integer thumbCount;

    /**
     * 创建时间
     */
    private Date createTime;

    /**
     * 博客摘要（Agent 自动生成）
     */
    private String summary;

    /**
     * 标签（Agent 推荐）
     */
    private String tags;

    /**
     * 是否已点赞
     */
    private Boolean hasThumb;

}
