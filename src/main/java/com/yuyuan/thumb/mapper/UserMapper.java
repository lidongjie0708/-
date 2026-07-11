package com.yuyuan.thumb.mapper;

import com.yuyuan.thumb.model.entity.User;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

/**
 * @author pine
 */
@Mapper
public interface UserMapper extends BaseMapper<User> {
    @Select("SELECT id FROM `user` WHERE username = #{username}")
    Long selectByUsername(String username);
}



