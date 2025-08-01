package de.mohadipe.data.recording.verbrauch.view.model;

import de.mohadipe.data.recording.verbrauch.domain.Messwerte;

import java.math.BigDecimal;
import java.time.LocalDate;

public record MesswertDto(String geraeteNummer, LocalDate datum, BigDecimal wert, String einheit) {
    public static MesswertDto from(Messwerte messwerte) {
        return new MesswertDto(
                messwerte.getZaehler().getGeraeteNr(),
                messwerte.getDatum(),
                messwerte.getWert(),
                messwerte.getEinheit() == null ? "" : messwerte.getEinheit()
        );
    }
}
