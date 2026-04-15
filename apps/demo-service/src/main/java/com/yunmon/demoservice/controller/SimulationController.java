package com.yunmon.demoservice.controller;

import com.yunmon.demoservice.service.BusinessMetricService;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.time.Instant;
import java.util.Map;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/demo")
public class SimulationController {

    private final BusinessMetricService businessMetricService;

    public SimulationController(BusinessMetricService businessMetricService) {
        this.businessMetricService = businessMetricService;
    }

    @GetMapping("/hello")
    public Map<String, Object> hello() {
        return Map.of(
                "service", "demo-service",
                "message", "Yun-mon demo service is running",
                "timestamp", Instant.now().toString());
    }

    @GetMapping("/healthz")
    public Map<String, Object> healthz() {
        return Map.of(
                "status", "UP",
                "queueDepth", businessMetricService.currentQueueDepth(),
                "timestamp", Instant.now().toString());
    }

    @PostMapping("/simulate")
    public SimulationResult simulate(
            @RequestParam(defaultValue = "5") @Min(1) @Max(100) int count,
            @RequestParam(defaultValue = "200") @Min(0) @Max(5000) long delayMs,
            @RequestParam(defaultValue = "false") boolean fail) {
        return businessMetricService.simulate(count, delayMs, fail);
    }

    @GetMapping("/error")
    public SimulationResult simulateError(
            @RequestParam(defaultValue = "1") @Min(1) @Max(10) int count,
            @RequestParam(defaultValue = "100") @Min(0) @Max(3000) long delayMs) {
        return businessMetricService.simulate(count, delayMs, true);
    }

    public record SimulationResult(
            String status,
            int processedCount,
            int queueDepth,
            long durationMs,
            String completedAt) {
    }
}

