package com.yunmon.demoservice.controller;

import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class SimulationControllerIT {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void helloEndpointReturnsServiceMetadata() throws Exception {
        mockMvc.perform(get("/api/demo/hello"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.service").value("demo-service"))
                .andExpect(jsonPath("$.timestamp").exists());
    }

    @Test
    void healthzReturnsUp() throws Exception {
        mockMvc.perform(get("/api/demo/healthz"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("UP"))
                .andExpect(jsonPath("$.queueDepth").isNumber());
    }

    @Test
    void simulateSuccessReturnsExpectedShape() throws Exception {
        mockMvc.perform(post("/api/demo/simulate").param("count", "3").param("delayMs", "0"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("SUCCESS"))
                .andExpect(jsonPath("$.processedCount").value(3))
                .andExpect(jsonPath("$.queueDepth").value(0))
                .andExpect(jsonPath("$.durationMs").isNumber());
    }

    @Test
    void simulateFailureSurfacesError() throws Exception {
        mockMvc.perform(post("/api/demo/simulate")
                .param("count", "2")
                .param("delayMs", "0")
                .param("fail", "true"))
                .andExpect(status().is5xxServerError());
    }

    @Test
    void prometheusEndpointExposesBusinessMetrics() throws Exception {
        mockMvc.perform(get("/actuator/prometheus"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("yunmon_business_orders_processed_total")))
                .andExpect(content().string(containsString("yunmon_business_queue_depth")));
    }
}
