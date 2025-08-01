package de.mohadipe.data.recording.verbrauch.domain;

import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Slice;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

public interface MesswerteRepository extends JpaRepository<Messwerte, Integer>, JpaSpecificationExecutor<Messwerte> {

    Slice<Messwerte> findAllBy(Pageable pageable);

    Slice<Messwerte> findByZaehlerId(Long zaehlerId, Pageable pageable);
}