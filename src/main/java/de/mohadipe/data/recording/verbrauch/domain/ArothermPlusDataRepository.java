package de.mohadipe.data.recording.verbrauch.domain;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

public interface ArothermPlusDataRepository extends JpaRepository<ArothermPlusData, Long>, JpaSpecificationExecutor<ArothermPlusData> {
}
