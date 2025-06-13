package de.mohadipe.data.recording.wertpapiere.service;

import de.mohadipe.data.recording.wertpapiere.domain.Etf;
import de.mohadipe.data.recording.wertpapiere.domain.EtfRepository;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(propagation = Propagation.REQUIRES_NEW)
public class EtfService {

    private final EtfRepository etfRepository;

    EtfService(EtfRepository etfRepository) {
        this.etfRepository = etfRepository;
    }

    public void createEtf(String wkn) {
        if ("fail".equals(wkn)) {
            throw new RuntimeException("This is for testing the error handler");
        }
        var etf = new Etf();
        etf.setWkn(wkn);
        etfRepository.saveAndFlush(etf);
    }

    public List<Etf> list(Pageable pageable) {
        return etfRepository.findAllBy(pageable).toList();
    }

}
