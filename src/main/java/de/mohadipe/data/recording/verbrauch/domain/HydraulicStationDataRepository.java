package de.mohadipe.data.recording.verbrauch.domain;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

import java.time.LocalDateTime;

public interface HydraulicStationDataRepository extends JpaRepository<HydraulicStationData, Long>, JpaSpecificationExecutor<HydraulicStationData> {
    boolean existsByDateTime(LocalDateTime dateTime);
}
