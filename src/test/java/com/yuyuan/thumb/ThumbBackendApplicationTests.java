package com.yuyuan.thumb;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ThumbBackendApplicationTests {

    @Test
    void applicationEntryPointExists() {
        assertThat(ThumbBackendApplication.class).isNotNull();
    }
}
