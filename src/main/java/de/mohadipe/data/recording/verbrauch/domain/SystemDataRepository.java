package de.mohadipe.data.recording.verbrauch.domain;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

import java.time.LocalDateTime;

public interface SystemDataRepository extends JpaRepository<SystemData, Long>, JpaSpecificationExecutor<SystemData> {
    boolean existsByDateTime(LocalDateTime dateTime);
}
