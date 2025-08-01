package de.mohadipe.data.recording.verbrauch.domain;

import de.mohadipe.data.recording.base.domain.AbstractEntity;
import jakarta.persistence.*;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import org.jspecify.annotations.Nullable;

import java.math.BigDecimal;
import java.time.LocalDate;

@Entity
@Table(name = "messwerte")
public class Messwerte extends AbstractEntity<Long> {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id", nullable = false)
    private Long id;

    @NotNull
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "zaehler_id", nullable = false)
    private Zaehler zaehler;

    @NotNull
    @Column(name = "datum", nullable = false)
    private LocalDate datum;

    @NotNull
    @Column(name = "wert", nullable = false, precision = 10, scale = 2)
    private BigDecimal wert;

    @Size(max = 255)
    @NotNull
    @Column(name = "einheit", nullable = false)
    private String einheit;

    public void setId(Long id) {
        this.id = id;
    }

    public Zaehler getZaehler() {
        return zaehler;
    }

    public void setZaehler(Zaehler zaehler) {
        this.zaehler = zaehler;
    }

    public LocalDate getDatum() {
        return datum;
    }

    public void setDatum(LocalDate datum) {
        this.datum = datum;
    }

    public BigDecimal getWert() {
        return wert;
    }

    public void setWert(BigDecimal wert) {
        this.wert = wert;
    }

    public String getEinheit() {
        return einheit;
    }

    public void setEinheit(String einheit) {
        this.einheit = einheit;
    }

    @Override
    public @Nullable Long getId() {
        return id;
    }
}