package de.mohadipe.data.recording.verbrauch.domain;

import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Slice;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

public interface ZaehlerRepository extends JpaRepository<Zaehler, Integer>, JpaSpecificationExecutor<Zaehler> {

    Slice<Zaehler> findAllBy(Pageable pageable);
}