package de.mohadipe.data.recording.wertpapiere.service;

import de.mohadipe.data.recording.wertpapiere.domain.WknInvestDatum;
import de.mohadipe.data.recording.wertpapiere.domain.WknInvestDatumRepository;
import de.mohadipe.data.recording.wertpapiere.ui.view.WknInvestDatumDTO;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class WknInvestDatumService {

    private final WknInvestDatumRepository wknInvestDatumRepository;

    WknInvestDatumService(WknInvestDatumRepository wknInvestDatumRepository) {
        this.wknInvestDatumRepository = wknInvestDatumRepository;
    }

    @Transactional(readOnly = false)
    public void createWknInvest(WknInvestDatum wknInvestDatum) {
        wknInvestDatumRepository.saveAndFlush(wknInvestDatum);
    }

    public List<WknInvestDatum> list(Pageable pageable) {
        return wknInvestDatumRepository.findAllBy(pageable).toList();
    }

    public List<WknInvestDatumDTO> listAsDTO(Pageable pageable) {
        return wknInvestDatumRepository.findAll(pageable)
                .stream()
                .map(WknInvestDatumDTO::from)
                .toList();
    }

    public List<WknInvestDatumDTO> listByWknAsDTO(Long wknId, Pageable pageable) {
        return wknInvestDatumRepository.findByWknId(wknId, pageable)
                .stream()
                .map(WknInvestDatumDTO::from)
                .toList();
    }
}
