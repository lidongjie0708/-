package com.yuyuan.thumb.common;

import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.MethodParameter;
import org.springframework.http.MediaType;
import org.springframework.http.converter.HttpMessageConverter;
import org.springframework.http.server.ServerHttpRequest;
import org.springframework.http.server.ServerHttpResponse;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;
import org.springframework.web.servlet.mvc.method.annotation.ResponseBodyAdvice;

@ControllerAdvice
public class HttpStatusResponseAdvice implements ResponseBodyAdvice<Object> {

    @Override
    public boolean supports(MethodParameter returnType, Class<? extends HttpMessageConverter<?>> converterType) {
        return true;
    }

    @Override
    public Object beforeBodyWrite(
            Object body,
            MethodParameter returnType,
            MediaType selectedContentType,
            Class<? extends HttpMessageConverter<?>> selectedConverterType,
            ServerHttpRequest request,
            ServerHttpResponse response) {
        if (body instanceof BaseResponse<?> baseResponse) {
            HttpServletResponse servletResponse = currentResponse();
            if (servletResponse != null && !servletResponse.isCommitted()) {
                servletResponse.setStatus(resolveHttpStatus(baseResponse.getCode()));
            }
        }
        return body;
    }

    private HttpServletResponse currentResponse() {
        if (RequestContextHolder.getRequestAttributes() instanceof ServletRequestAttributes attributes) {
            return attributes.getResponse();
        }
        return null;
    }

    private int resolveHttpStatus(int code) {
        if (code == 0) {
            return 200;
        }
        if (code >= 100 && code <= 599) {
            return code;
        }
        if (code >= 40000 && code < 50000) {
            return code / 100;
        }
        if (code >= 50000 && code < 60000) {
            return 500;
        }
        return 500;
    }
}
