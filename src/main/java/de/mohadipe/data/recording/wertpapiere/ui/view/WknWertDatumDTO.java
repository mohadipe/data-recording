package de.mohadipe.data.recording.wertpapiere.ui.view;

import de.mohadipe.data.recording.wertpapiere.domain.WknWertDatum;

import java.math.BigDecimal;
import java.time.LocalDate;

public record WknWertDatumDTO(String wknNummer, LocalDate datum, BigDecimal wert) {
    public static WknWertDatumDTO from(WknWertDatum entity) {
        return new WknWertDatumDTO(
                entity.getWkn().getWkn(),
                entity.getDatum(),
                entity.getWert()
        );
    }
}
