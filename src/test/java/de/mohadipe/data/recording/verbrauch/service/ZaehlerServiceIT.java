package de.mohadipe.data.recording.verbrauch.service;

import de.mohadipe.data.recording.TestcontainersConfiguration;
import de.mohadipe.data.recording.verbrauch.domain.ZaehlerRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Profile;
import org.springframework.data.domain.PageRequest;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@Import(TestcontainersConfiguration.class)
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.MOCK)
@Transactional(propagation = Propagation.NOT_SUPPORTED)
@Profile("test")
class ZaehlerServiceIT {

    @Autowired
    ZaehlerService zaehlerService;

    @Autowired
    ZaehlerRepository zaehlerRepository;

    @AfterEach
    void cleanUp() {
        zaehlerRepository.deleteAll();
    }

    @Test
    public void zaehler_are_stored_in_the_database() {
        zaehlerService.createZaehler("Do this", LocalDate.now(), LocalDate.now(), "strom");
        assertThat(zaehlerService.list(PageRequest.ofSize(1))).singleElement()
                .matches(zaehler -> zaehler.getGeraeteNr().equals("Do this"));
    }

    @Test
    public void zaehler_are_validated_before_they_are_stored() {
        assertThatThrownBy(() -> zaehlerService.createZaehler("fail", LocalDate.now(), LocalDate.now(), "wasser"))
                .isInstanceOf(RuntimeException.class);
        assertThat(zaehlerRepository.count()).isEqualTo(0);
    }
}
