package de.mohadipe.data.recording.verbrauch.service;

import de.mohadipe.data.recording.verbrauch.domain.Kosten;
import de.mohadipe.data.recording.verbrauch.domain.KostenRepository;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

@Service
@Transactional(propagation = Propagation.REQUIRES_NEW)
public class KostenService {

    private final KostenRepository kostenRepository;

    KostenService(KostenRepository kostenRepository) {
        this.kostenRepository = kostenRepository;
    }

    public List<Kosten> list(Pageable pageable) {
        return kostenRepository.findAllBy(pageable).toList();
    }

    public void createKosten(String ressource, LocalDate von, LocalDate bis, BigDecimal preis, String einheit) {
        if ("fail".equals(ressource)) {
            throw new RuntimeException("This is for testing the error handler");
        }
        var kosten = new Kosten();
        kosten.setRessource(ressource);
        kosten.setVon(von);
        kosten.setBis(bis);
        kosten.setPreis(preis);
        kosten.setEinheit(einheit);
        kostenRepository.saveAndFlush(kosten);
    }
}
