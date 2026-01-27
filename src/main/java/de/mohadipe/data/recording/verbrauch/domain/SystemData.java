package de.mohadipe.data.recording.verbrauch.domain;

import de.mohadipe.data.recording.base.domain.AbstractEntity;
import jakarta.persistence.*;
import jakarta.validation.constraints.NotNull;
import org.springframework.lang.Nullable;

import java.time.LocalDateTime;

@Entity
@Table(name = "system_data")
public class SystemData extends AbstractEntity<Long> {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id", nullable = false)
    private Long id;

    @NotNull
    @Column(name = "date_time", nullable = false)
    private LocalDateTime dateTime;

    @Column(name = "outdoor_temperature")
    private Double outdoorTemperature;

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

    public Double getOutdoorTemperature() {
        return outdoorTemperature;
    }

    public void setOutdoorTemperature(Double outdoorTemperature) {
        this.outdoorTemperature = outdoorTemperature;
    }
}
