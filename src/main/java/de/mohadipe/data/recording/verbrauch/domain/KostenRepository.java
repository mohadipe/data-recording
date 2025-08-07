package de.mohadipe.data.recording.verbrauch.domain;

import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Slice;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

public interface KostenRepository extends JpaRepository<Kosten, Integer>, JpaSpecificationExecutor<Kosten> {

    Slice<Kosten> findAllBy(Pageable pageable);
}