package de.mohadipe.data.recording.verbrauch.service;

import de.mohadipe.data.recording.verbrauch.domain.HydraulicStationData;
import de.mohadipe.data.recording.verbrauch.domain.HydraulicStationDataRepository;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class HydraulicStationDataService {

    private final HydraulicStationDataRepository hydraulicStationDataRepository;

    public HydraulicStationDataService(HydraulicStationDataRepository hydraulicStationDataRepository) {
        this.hydraulicStationDataRepository = hydraulicStationDataRepository;
    }

    public List<HydraulicStationData> list(Pageable pageable) {
        return hydraulicStationDataRepository.findAll(pageable).toList();
    }

    @Transactional
    public ImportResult importData(List<HydraulicStationData> dataList) {
        int imported = 0;
        int ignored = 0;
        for (HydraulicStationData data : dataList) {
            if (!hydraulicStationDataRepository.existsByDateTime(data.getDateTime())) {
                hydraulicStationDataRepository.save(data);
                imported++;
            } else {
                ignored++;
            }
        }
        return new ImportResult(imported, ignored);
    }
}
