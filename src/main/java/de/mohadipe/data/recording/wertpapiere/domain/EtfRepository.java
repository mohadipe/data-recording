package de.mohadipe.data.recording.wertpapiere.domain;

import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Slice;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

public interface EtfRepository extends JpaRepository<Etf, Long>, JpaSpecificationExecutor<Etf> {

    // If you don't need a total row count, Slice is better than Page.
    Slice<Etf> findAllBy(Pageable pageable);
}
