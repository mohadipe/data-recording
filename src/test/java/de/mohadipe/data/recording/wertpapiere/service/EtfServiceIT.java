package de.mohadipe.data.recording.wertpapiere.service;

import de.mohadipe.data.recording.TestcontainersConfiguration;
import de.mohadipe.data.recording.wertpapiere.domain.Etf;
import de.mohadipe.data.recording.wertpapiere.domain.EtfRepository;
import jakarta.validation.ValidationException;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.data.domain.PageRequest;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@Import(TestcontainersConfiguration.class)
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.MOCK)
@Transactional(propagation = Propagation.NOT_SUPPORTED)
class EtfServiceIT {

    @Autowired
    EtfService etfService;

    @Autowired
    EtfRepository etfRepository;

    @AfterEach
    void cleanUp() {
        etfRepository.deleteAll();
    }

    @Test
    public void etfs_are_stored_in_the_database() {
        etfService.createEtf("Do this");
        assertThat(etfService.list(PageRequest.ofSize(1))).singleElement()
                .matches(etf -> etf.getWkn().equals("Do this"));
    }

    @Test
    public void etfs_are_validated_before_they_are_stored() {
        assertThatThrownBy(() -> etfService.createEtf("X".repeat(Etf.DESCRIPTION_MAX_LENGTH + 1)))
                .isInstanceOf(ValidationException.class);
        assertThat(etfRepository.count()).isEqualTo(0);
    }
}
