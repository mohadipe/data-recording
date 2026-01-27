package de.mohadipe.data.recording.verbrauch.domain;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

import java.time.LocalDateTime;

public interface ArothermPlusDataRepository extends JpaRepository<ArothermPlusData, Long>, JpaSpecificationExecutor<ArothermPlusData> {
    boolean existsByDateTime(LocalDateTime dateTime);
}
