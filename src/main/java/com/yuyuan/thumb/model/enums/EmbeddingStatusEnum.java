package com.yuyuan.thumb.model.enums;

import lombok.Getter;

/**
 * 博客向量化状态枚举
 * 用于 RAG 知识库构建，标记博客是否已经生成向量存入向量数据库
 */
@Getter
public enum EmbeddingStatusEnum {
    /**
     * 未处理（需要 Agent 处理）
     */
    UNPROCESSED(0, "未处理"),
    /**
     * 处理中（Agent 正在处理，避免重复处理）
     */
    PROCESSING(1, "处理中"),
    /**
     * 已完成（已经向量化入库）
     */
    COMPLETED(2, "已完成"),
    /**
     * 处理失败（记录失败，便于重试）
     */
    FAILED(3, "处理失败");

    private final int code;
    private final String desc;

    EmbeddingStatusEnum(int code, String desc) {
        this.code = code;
        this.desc = desc;
    }
}
