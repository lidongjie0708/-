package com.yuyuan.thumb.model.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.util.Date;
import lombok.Data;
import lombok.Getter;
import lombok.Setter;

/**
 * 
 * @TableName blog
 */
@TableName(value ="blog")
@Data
@Getter
@Setter
public class Blog {
    public Long getUserId() {
        return userId;
    }

    public void setUserId(Long userId) {
        this.userId = userId;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getCoverImg() {
        return coverImg;
    }

    public void setCoverImg(String coverImg) {
        this.coverImg = coverImg;
    }

    public String getContent() {
        return content;
    }

    public void setContent(String content) {
        this.content = content;
    }

    public Integer getThumbCount() {
        return thumbCount;
    }

    public void setThumbCount(Integer thumbCount) {
        this.thumbCount = thumbCount;
    }

    public Date getCreateTime() {
        return createTime;
    }

    public void setCreateTime(Date createTime) {
        this.createTime = createTime;
    }

    public Date getUpdateTime() {
        return updateTime;
    }

    public void setUpdateTime(Date updateTime) {
        this.updateTime = updateTime;
    }

    /**
     * 
     */
    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    @TableField("userId")
    private Long userId;

    /**
     * 标题
     */
    private String title;

    /**
     * 封面
     */
    @TableField("coverImg")
    private String coverImg;

    /**
     * 内容
     */
    private String content;

    /**
     * Content storage format. Currently supports PLAIN and MARKDOWN.
     * Markdown is stored as source text and rendered through a sanitizer by clients.
     */
    @TableField("content_format")
    private String contentFormat;

    /**
     * 点赞数
     */
    @TableField("thumbCount")
    private Integer thumbCount;

    /**
     * 博客摘要（Agent 自动生成）
     */
    private String summary;

    /**
     * 标签（Agent 推荐，逗号分隔）
     */
    private String tags;

    /**
     * 向量化状态（0-未处理 1-处理中 2-已完成 3-失败）
     * @see com.yuyuan.thumb.model.enums.EmbeddingStatusEnum
     */
    @TableField("embedding_status")
    private Integer embeddingStatus;

    /**
     * 审核状态（0-待审核 1-通过 2-拒绝）
     * @see com.yuyuan.thumb.model.enums.AuditStatusEnum
     */
    @TableField("audit_status")
    private Integer auditStatus;

    /**
     * 创建时间
     */
    @TableField("createTime")
    private Date createTime;

    /**
     * 更新时间
     */
    @TableField("updateTime")
    private Date updateTime;
}
