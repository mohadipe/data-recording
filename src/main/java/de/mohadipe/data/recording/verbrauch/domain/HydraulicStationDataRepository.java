package de.mohadipe.data.recording.verbrauch.domain;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

public interface HydraulicStationDataRepository extends JpaRepository<HydraulicStationData, Long>, JpaSpecificationExecutor<HydraulicStationData> {
}
