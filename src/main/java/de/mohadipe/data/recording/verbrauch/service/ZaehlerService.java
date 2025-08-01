package de.mohadipe.data.recording.verbrauch.service;

import de.mohadipe.data.recording.verbrauch.domain.Zaehler;
import de.mohadipe.data.recording.verbrauch.domain.ZaehlerRepository;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;

@Service
@Transactional(propagation = Propagation.REQUIRES_NEW)
public class ZaehlerService {

    private final ZaehlerRepository zaehlerRepository;

    ZaehlerService(ZaehlerRepository zaehlerRepository) {
        this.zaehlerRepository = zaehlerRepository;
    }

    public List<Zaehler> list(Pageable pageable) {
        return zaehlerRepository.findAllBy(pageable).toList();
    }

    public void createZaehler(String geraeteNr, LocalDate einBauDt, LocalDate ausBauDt, String typ) {
        if ("fail".equals(geraeteNr)) {
            throw new RuntimeException("This is for testing the error handler");
        }
        var zaehler = new Zaehler();
        zaehler.setGeraeteNr(geraeteNr);
        zaehler.setEinbauDt(einBauDt);
        zaehler.setAusbauDt(ausBauDt);
        zaehler.setTyp(typ);
        zaehlerRepository.saveAndFlush(zaehler);
    }
}
