FROM maven:3.9.9-eclipse-temurin-17 AS build
WORKDIR /workspace

COPY pom.xml .
COPY src ./src

RUN mvn -B -DskipTests package

FROM eclipse-temurin:17-jre
WORKDIR /app

ENV APP_LOG_DIR=/var/log/yunmon
ENV JAVA_OPTS=""

RUN mkdir -p /var/log/yunmon

COPY --from=build /workspace/target/demo-service-0.1.0-SNAPSHOT.jar /app/app.jar

EXPOSE 8080

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar /app/app.jar"]

