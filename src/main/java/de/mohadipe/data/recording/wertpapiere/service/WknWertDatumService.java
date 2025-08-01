package de.mohadipe.data.recording.wertpapiere.service;

import de.mohadipe.data.recording.wertpapiere.domain.WknWertDatum;
import de.mohadipe.data.recording.wertpapiere.domain.WknWertDatumRepository;
import de.mohadipe.data.recording.wertpapiere.view.model.WknWertDatumDTO;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class WknWertDatumService {

    private final WknWertDatumRepository wknWertDatumRepository;

    WknWertDatumService(WknWertDatumRepository wknWertDatumRepository) {
        this.wknWertDatumRepository = wknWertDatumRepository;
    }

    @Transactional(readOnly = false)
    public void createWknInvest(WknWertDatum wknWertDatum) {
        wknWertDatumRepository.saveAndFlush(wknWertDatum);
    }

    public List<WknWertDatum> list(Pageable pageable) {
        return wknWertDatumRepository.findAllBy(pageable).toList();
    }

    public List<WknWertDatumDTO> listAsDTO(Pageable pageable) {
        return wknWertDatumRepository.findAll(pageable)
                .stream()
                .map(WknWertDatumDTO::from)
                .toList();
    }

    public List<WknWertDatumDTO> listByWknAsDTO(Long wknId, Pageable pageable) {
        return wknWertDatumRepository.findByWknId(wknId, pageable)
                .stream()
                .map(WknWertDatumDTO::from)
                .toList();
    }
}
