package de.mohadipe.data.recording.verbrauch.service;

import de.mohadipe.data.recording.verbrauch.domain.SystemData;
import de.mohadipe.data.recording.verbrauch.domain.SystemDataRepository;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class SystemDataService {

    private final SystemDataRepository systemDataRepository;

    public SystemDataService(SystemDataRepository systemDataRepository) {
        this.systemDataRepository = systemDataRepository;
    }

    public List<SystemData> list(Pageable pageable) {
        return systemDataRepository.findAll(pageable).toList();
    }

    @Transactional
    public ImportResult importData(List<SystemData> dataList) {
        int imported = 0;
        int ignored = 0;
        for (SystemData data : dataList) {
            if (!systemDataRepository.existsByDateTime(data.getDateTime())) {
                systemDataRepository.save(data);
                imported++;
            } else {
                ignored++;
            }
        }
        return new ImportResult(imported, ignored);
    }
}
