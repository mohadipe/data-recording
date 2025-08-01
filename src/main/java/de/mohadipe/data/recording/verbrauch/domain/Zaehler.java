package de.mohadipe.data.recording.verbrauch.domain;

import de.mohadipe.data.recording.base.domain.AbstractEntity;
import jakarta.persistence.*;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import org.jspecify.annotations.Nullable;

import java.time.LocalDate;

@Entity
@Table(name = "zaehler")
public class Zaehler extends AbstractEntity<Long> {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id", nullable = false)
    private Long id;

    @Size(max = 255)
    @NotNull
    @Column(name = "geraete_nr", nullable = false)
    private String geraeteNr;

    @NotNull
    @Column(name = "einbau_dt", nullable = false)
    private LocalDate einbauDt;

    @NotNull
    @Column(name = "ausbau_dt", nullable = false)
    private LocalDate ausbauDt;

    @Size(max = 255)
    @NotNull
    @Column(name = "typ", nullable = false)
    private String typ;

    public String getGeraeteNr() {
        return geraeteNr;
    }

    public void setGeraeteNr(String geraeteNr) {
        this.geraeteNr = geraeteNr;
    }

    public LocalDate getEinbauDt() {
        return einbauDt;
    }

    public void setEinbauDt(LocalDate einbauDt) {
        this.einbauDt = einbauDt;
    }

    public LocalDate getAusbauDt() {
        return ausbauDt;
    }

    public void setAusbauDt(LocalDate ausbauDt) {
        this.ausbauDt = ausbauDt;
    }

    public String getTyp() {
        return typ;
    }

    public void setTyp(String typ) {
        this.typ = typ;
    }

    @Override
    public @Nullable Long getId() {
        return id;
    }
}