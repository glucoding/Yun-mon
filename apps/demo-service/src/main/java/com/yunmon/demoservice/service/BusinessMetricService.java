package com.yunmon.demoservice.service;

import com.yunmon.demoservice.controller.SimulationController.SimulationResult;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import java.time.Instant;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class BusinessMetricService {

    private static final Logger log = LoggerFactory.getLogger(BusinessMetricService.class);

    private final AtomicInteger queueDepth = new AtomicInteger(0);
    private final Counter processedCounter;
    private final Counter failedCounter;
    private final Timer processingTimer;

    public BusinessMetricService(MeterRegistry meterRegistry) {
        this.processedCounter = Counter.builder("yunmon_business_orders_processed_total")
                .description("Total number of successfully processed demo orders")
                .register(meterRegistry);
        this.failedCounter = Counter.builder("yunmon_business_orders_failed_total")
                .description("Total number of failed demo orders")
                .register(meterRegistry);
        this.processingTimer = Timer.builder("yunmon_business_processing_seconds")
                .description("Business processing latency for the demo workload")
                .publishPercentileHistogram()
                .register(meterRegistry);

        Gauge.builder("yunmon_business_queue_depth", queueDepth, AtomicInteger::get)
                .description("Current depth of the simulated business queue")
                .register(meterRegistry);
    }

    public int currentQueueDepth() {
        return queueDepth.get();
    }

    public SimulationResult simulate(int count, long delayMs, boolean fail) {
        long normalizedDelay = Math.max(0, Math.min(delayMs, 5000));
        long startedAt = System.nanoTime();
        int queued = queueDepth.addAndGet(count);

        log.info("event=simulation_start app=demo-service count={} fail={} delayMs={} queueDepth={}",
                count, fail, normalizedDelay, queued);

        try {
            SimulationResult result = processingTimer.record(() -> {
                sleep(normalizedDelay);
                if (fail) {
                    failedCounter.increment(count);
                    throw new IllegalStateException("Simulated business failure for alert verification");
                }
                processedCounter.increment(count);
                // 成功路径在闭包内扣减队列深度,避免与异常分支双重扣减,确保返回的 queueDepth 与外部一致。
                int remainingQueueDepth = Math.max(queueDepth.addAndGet(-count), 0);
                long durationMs = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - startedAt);
                return new SimulationResult(
                        "SUCCESS",
                        count,
                        remainingQueueDepth,
                        durationMs,
                        Instant.now().toString());
            });

            log.info("event=simulation_success app=demo-service count={} durationMs={}",
                    count, result.durationMs());
            return result;
        } catch (RuntimeException ex) {
            queueDepth.addAndGet(-count);
            long durationMs = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - startedAt);
            log.error("event=simulation_failed app=demo-service count={} durationMs={} message={}",
                    count, durationMs, ex.getMessage());
            throw ex;
        }
    }

    private void sleep(long delayMs) {
        try {
            Thread.sleep(delayMs);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Business simulation interrupted", ex);
        }
    }
}
