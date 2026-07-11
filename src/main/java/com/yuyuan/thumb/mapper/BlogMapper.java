package com.yuyuan.thumb.mapper;

import com.yuyuan.thumb.model.entity.Blog;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

/**
 * @author pine
 */
@Mapper
public interface BlogMapper extends BaseMapper<Blog> {
    void batchUpdateThumbCount(@Param("countMap") Map<Long, Long> countMap);
    
    @Select("SELECT * FROM blog WHERE userId = #{userId}")
    List<Blog> selectByAuthorId(Long userId);
}



