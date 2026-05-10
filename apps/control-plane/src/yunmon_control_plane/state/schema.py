"""desired-state 的 Pydantic 模型(P1-2 替代手写 validate_state)。"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PortNumber = Annotated[int, Field(ge=1, le=65535)]
NonEmptyStr = Annotated[str, Field(min_length=1)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Metadata(_Model):
    schemaVersion: int = 2
    lastAppliedAt: datetime | None = None


class SystemConfig(_Model):
    monitoringProject: NonEmptyStr
    environment: NonEmptyStr
    clusterName: NonEmptyStr


class ClusterConfig(_Model):
    id: NonEmptyStr
    name: NonEmptyStr
    type: Literal["docker-compose", "kubernetes"]
    isPrimary: bool = False
    description: str = ""


class PortsConfig(_Model):
    grafanaHostPort: PortNumber
    demoServiceHostPort: PortNumber
    controlPlaneHostPort: PortNumber
    prometheusHostPort: PortNumber
    alertmanagerHostPort: PortNumber
    lokiHostPort: PortNumber
    cadvisorHostPort: PortNumber
    otelCollectorOtlpHttpPort: PortNumber = 4318
    otelCollectorOtlpGrpcPort: PortNumber = 4317


class GrafanaConfig(_Model):
    adminUser: NonEmptyStr
    adminPassword: NonEmptyStr
    allowSignUp: bool


class DemoServiceConfig(_Model):
    appEnv: NonEmptyStr
    logDir: NonEmptyStr
    javaOpts: NonEmptyStr
    monitoringEnabled: bool
    monitoringPort: PortNumber
    serviceName: NonEmptyStr
    metricsPath: NonEmptyStr


class ApplicationDefaults(_Model):
    enabled: bool
    metricsPath: NonEmptyStr
    environment: NonEmptyStr


class ApplicationItem(_Model):
    appId: NonEmptyStr
    enabled: bool
    displayName: str = ""
    serviceName: str = ""
    targetPort: PortNumber | None = None
    metricsPath: NonEmptyStr
    environment: NonEmptyStr


class ApplicationsConfig(_Model):
    autoDiscoveryEnabled: bool
    defaults: ApplicationDefaults
    items: list[ApplicationItem] = Field(default_factory=list)

    @field_validator("items")
    @classmethod
    def _unique_app_id(cls, value: list[ApplicationItem]) -> list[ApplicationItem]:
        ids = [item.appId for item in value]
        duplicates = {item for item in ids if ids.count(item) > 1}
        if duplicates:
            raise ValueError(f"applications.items 出现重复 appId: {sorted(duplicates)}")
        return value


class MetricVisualization(_Model):
    panelType: Literal["timeseries", "stat", "gauge"]
    unit: NonEmptyStr
    decimals: Annotated[int, Field(ge=0, le=10)] = 0
    colorMode: NonEmptyStr
    showOnDashboard: bool = False


class MetricCategory(_Model):
    id: NonEmptyStr
    name: NonEmptyStr
    description: str = ""


class MetricItem(_Model):
    metricId: NonEmptyStr
    metricName: NonEmptyStr
    displayName: NonEmptyStr
    category: NonEmptyStr
    sourceType: Literal["raw", "recording_rule"]
    ruleMode: Literal["external", "managed"]
    description: NonEmptyStr
    expression: str = ""
    derivedFrom: list[str] = Field(default_factory=list)
    unit: NonEmptyStr
    enabled: bool = True
    visualization: MetricVisualization

    @model_validator(mode="after")
    def _check_managed_expression(self) -> MetricItem:
        if self.sourceType == "recording_rule" and self.ruleMode == "managed" and not self.expression.strip():
            raise ValueError(f"metricCatalog.items[{self.metricId}].expression 必填(managed recording_rule)")
        return self


class MetricCatalog(_Model):
    categories: list[MetricCategory] = Field(min_length=1)
    items: list[MetricItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_unique(self) -> MetricCatalog:
        category_ids = [c.id for c in self.categories]
        cat_dups = {item for item in category_ids if category_ids.count(item) > 1}
        if cat_dups:
            raise ValueError(f"metricCatalog.categories 出现重复 id: {sorted(cat_dups)}")
        cat_set = set(category_ids)
        ids = [item.metricId for item in self.items]
        names = [item.metricName for item in self.items]
        for label, values in (("metricId", ids), ("metricName", names)):
            duplicates = {value for value in values if values.count(value) > 1}
            if duplicates:
                raise ValueError(f"metricCatalog.items 出现重复 {label}: {sorted(duplicates)}")
        for item in self.items:
            if item.category not in cat_set:
                raise ValueError(f"metricCatalog.items[{item.metricId}].category 引用了未知分类 {item.category}")
        return self


class PrometheusExternalLabels(_Model):
    cluster: NonEmptyStr
    env: NonEmptyStr


class PrometheusConfig(_Model):
    scrapeInterval: NonEmptyStr
    evaluationInterval: NonEmptyStr
    dockerDiscoveryRefreshInterval: NonEmptyStr
    externalLabels: PrometheusExternalLabels


class AlertmanagerConfig(_Model):
    resolveTimeout: NonEmptyStr
    groupBy: list[NonEmptyStr] = Field(min_length=1)
    groupWait: NonEmptyStr
    groupInterval: NonEmptyStr
    repeatInterval: NonEmptyStr


class AlertReceiverMatcher(_Model):
    severity: NonEmptyStr | None = None
    service: NonEmptyStr | None = None
    cluster: NonEmptyStr | None = None


class AlertReceiverConfig(_Model):
    name: NonEmptyStr
    kind: Literal["webhook", "email", "wework", "dingtalk", "feishu"]
    enabled: bool = False
    config: dict[str, Any] = Field(default_factory=dict)
    matchers: list[AlertReceiverMatcher] = Field(default_factory=list)


class LokiConfig(_Model):
    authEnabled: bool
    pathPrefix: NonEmptyStr
    replicationFactor: Annotated[int, Field(ge=1)]
    reportingEnabled: bool


class PromtailConfig(_Model):
    positionsFile: NonEmptyStr
    clientUrl: NonEmptyStr
    logPath: NonEmptyStr


class CadvisorConfig(_Model):
    dockerOnly: bool
    housekeepingInterval: NonEmptyStr


class OtelExporterConfig(_Model):
    logging: bool = True
    otlpHttpEndpoint: str = ""


class OtelCollectorConfig(_Model):
    enabled: bool = False
    exporters: OtelExporterConfig = Field(default_factory=OtelExporterConfig)


class StackAgentConfig(_Model):
    enabled: bool
    baseUrl: NonEmptyStr
    sharedToken: str = Field(min_length=16)


class SLODefinition(_Model):
    id: NonEmptyStr
    service: NonEmptyStr
    objective: Annotated[float, Field(gt=0, lt=1)]
    sliExpression: NonEmptyStr
    description: str = ""


class YunmonState(_Model):
    metadata: Metadata = Field(default_factory=Metadata)
    system: SystemConfig
    clusters: list[ClusterConfig] = Field(default_factory=list)
    ports: PortsConfig
    grafana: GrafanaConfig
    demoService: DemoServiceConfig
    applications: ApplicationsConfig
    metricCatalog: MetricCatalog
    prometheus: PrometheusConfig
    alertmanager: AlertmanagerConfig
    alertReceivers: list[AlertReceiverConfig] = Field(default_factory=list)
    loki: LokiConfig
    promtail: PromtailConfig
    cadvisor: CadvisorConfig
    otelCollector: OtelCollectorConfig = Field(default_factory=OtelCollectorConfig)
    stackAgent: StackAgentConfig
    slos: list[SLODefinition] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
