package de.mohadipe.data.recording.verbrauch.domain;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

public interface MesswerteRepository extends JpaRepository<Messwerte, Integer>, JpaSpecificationExecutor<Messwerte> {
}