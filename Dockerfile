FROM eclipse-temurin:21-jre
COPY target/*.jar app.jar
# Add a /logs volume
VOLUME ["/logs"]
EXPOSE 9015
ENTRYPOINT ["java", "-jar", "-Dspring.profiles.active=prod", "/app.jar"]
