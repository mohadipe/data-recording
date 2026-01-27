package de.mohadipe.data.recording.verbrauch.domain;

import de.mohadipe.data.recording.base.domain.AbstractEntity;
import jakarta.persistence.*;
import jakarta.validation.constraints.NotNull;
import org.springframework.lang.Nullable;

import java.time.LocalDateTime;

@Entity
@Table(name = "hydraulic_station_data")
public class HydraulicStationData extends AbstractEntity<Long> {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id", nullable = false)
    private Long id;

    @NotNull
    @Column(name = "date_time", nullable = false)
    private LocalDateTime dateTime;

    @Column(name = "consumed_electrical_energy_heating")
    private Double consumedElectricalEnergyHeating;

    @Column(name = "heat_generated_heating")
    private Double heatGeneratedHeating;

    @Override
    public @Nullable Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public LocalDateTime getDateTime() {
        return dateTime;
    }

    public void setDateTime(LocalDateTime dateTime) {
        this.dateTime = dateTime;
    }

    public Double getConsumedElectricalEnergyHeating() {
        return consumedElectricalEnergyHeating;
    }

    public void setConsumedElectricalEnergyHeating(Double consumedElectricalEnergyHeating) {
        this.consumedElectricalEnergyHeating = consumedElectricalEnergyHeating;
    }

    public Double getHeatGeneratedHeating() {
        return heatGeneratedHeating;
    }

    public void setHeatGeneratedHeating(Double heatGeneratedHeating) {
        this.heatGeneratedHeating = heatGeneratedHeating;
    }
}
