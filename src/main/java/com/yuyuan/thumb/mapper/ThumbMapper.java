package com.yuyuan.thumb.mapper;

import com.yuyuan.thumb.model.entity.Thumb;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * @author pine
 */
@Mapper
public interface ThumbMapper extends BaseMapper<Thumb> {

    int insertIgnore(@Param("thumb") Thumb thumb);

    int deleteByUserAndBlog(@Param("userId") Long userId, @Param("blogId") Long blogId);
}



