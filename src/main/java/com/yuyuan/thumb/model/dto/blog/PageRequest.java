package com.yuyuan.thumb.model.dto.blog;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
@Schema(description = "分页请求")
public class PageRequest {

    @Schema(description = "页码", example = "1")
    @NotNull(message = "页码不能为空")
    @Min(value = 1, message = "页码最小为1")
    private Integer pageNum;

    @Schema(description = "每页大小", example = "10")
    @NotNull(message = "每页大小不能为空")
    @Min(value = 1, message = "每页大小最小为1")
    @Max(value = 100, message = "每页最多查询100条")
    private Integer pageSize;

    @Schema(description = "排序字段", example = "createTime")
    private String sortField;

    @Schema(description = "Title/content keyword")
    private String keyword;

    @Schema(description = "Content format: PLAIN or MARKDOWN")
    private String contentFormat;

    public String getSortOrder() {
        return sortOrder;
    }

    public void setSortOrder(String sortOrder) {
        this.sortOrder = sortOrder;
    }

    public String getSortField() {
        return sortField;
    }

    public void setSortField(String sortField) {
        this.sortField = sortField;
    }

    public @NotNull(message = "每页大小不能为空") @Min(value = 1, message = "每页大小最小为1") Integer getPageSize() {
        return pageSize;
    }

    public void setPageSize(@NotNull(message = "每页大小不能为空") @Min(value = 1, message = "每页大小最小为1") Integer pageSize) {
        this.pageSize = pageSize;
    }

    public @NotNull(message = "页码不能为空") @Min(value = 1, message = "页码最小为1") Integer getPageNum() {
        return pageNum;
    }

    public void setPageNum(@NotNull(message = "页码不能为空") @Min(value = 1, message = "页码最小为1") Integer pageNum) {
        this.pageNum = pageNum;
    }

    @Schema(description = "排序方式", example = "desc")
    private String sortOrder;
}
