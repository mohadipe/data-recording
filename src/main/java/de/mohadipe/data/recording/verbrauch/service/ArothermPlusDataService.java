package de.mohadipe.data.recording.verbrauch.service;

import de.mohadipe.data.recording.verbrauch.domain.ArothermPlusData;
import de.mohadipe.data.recording.verbrauch.domain.ArothermPlusDataRepository;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class ArothermPlusDataService {

    private final ArothermPlusDataRepository arothermPlusDataRepository;

    public ArothermPlusDataService(ArothermPlusDataRepository arothermPlusDataRepository) {
        this.arothermPlusDataRepository = arothermPlusDataRepository;
    }

    public List<ArothermPlusData> list(Pageable pageable) {
        return arothermPlusDataRepository.findAll(pageable).toList();
    }
}
