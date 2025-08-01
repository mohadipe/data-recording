package de.mohadipe.data.recording.verbrauch.service;

import de.mohadipe.data.recording.verbrauch.domain.Messwerte;
import de.mohadipe.data.recording.verbrauch.domain.MesswerteRepository;
import de.mohadipe.data.recording.verbrauch.view.model.MesswertDto;
import de.mohadipe.data.recording.wertpapiere.domain.WknWertDatum;
import de.mohadipe.data.recording.wertpapiere.domain.WknWertDatumRepository;
import de.mohadipe.data.recording.wertpapiere.view.model.WknWertDatumDTO;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class MesswerteService {

    private final MesswerteRepository messwerteRepository;

    MesswerteService(MesswerteRepository messwerteRepository) {
        this.messwerteRepository = messwerteRepository;
    }

    @Transactional(readOnly = false)
    public void createMesswert(Messwerte messwerte) {
        messwerteRepository.saveAndFlush(messwerte);
    }

    public List<Messwerte> list(Pageable pageable) {
        return messwerteRepository.findAllBy(pageable).toList();
    }

    public List<MesswertDto> listAsDTO(Pageable pageable) {
        return messwerteRepository.findAll(pageable)
                .stream()
                .map(MesswertDto::from)
                .toList();
    }

    public List<MesswertDto> listByZaehlerAsDTO(Long zaehlerId, Pageable pageable) {
        return messwerteRepository.findByZaehlerId(zaehlerId, pageable)
                .stream()
                .map(MesswertDto::from)
                .toList();
    }

}
