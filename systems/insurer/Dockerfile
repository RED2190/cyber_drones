FROM maven:3.8.4-openjdk-17 AS builder

WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline -B
COPY src ./src
RUN mvn package -DskipTests -B

FROM eclipse-temurin:17 AS runtime
WORKDIR /app
COPY --from=builder /app/target/*.jar app.jar

COPY entrypoint.sh entrypoint.sh
RUN chmod +x entrypoint.sh \
	&& addgroup --system app \
	&& adduser --system --ingroup app app \
	&& chown -R app:app /app

USER app

ENTRYPOINT ["/app/entrypoint.sh"]