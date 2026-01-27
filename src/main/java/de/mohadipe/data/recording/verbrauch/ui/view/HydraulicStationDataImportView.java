package de.mohadipe.data.recording.verbrauch.ui.view;

import com.vaadin.flow.component.html.H2;
import com.vaadin.flow.component.html.Main;
import com.vaadin.flow.component.html.Paragraph;
import com.vaadin.flow.component.notification.Notification;
import com.vaadin.flow.component.notification.NotificationVariant;
import com.vaadin.flow.component.orderedlayout.VerticalLayout;
import com.vaadin.flow.component.upload.Upload;
import com.vaadin.flow.component.upload.receivers.MemoryBuffer;
import com.vaadin.flow.router.Menu;
import com.vaadin.flow.router.PageTitle;
import com.vaadin.flow.router.Route;
import de.mohadipe.data.recording.verbrauch.domain.HydraulicStationData;
import de.mohadipe.data.recording.verbrauch.service.HydraulicStationDataService;
import de.mohadipe.data.recording.verbrauch.service.ImportResult;
import jakarta.annotation.security.PermitAll;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

@Route("hydraulic-station-data-import")
@PageTitle("Hydraulic Station Data Import")
@Menu(order = 3, icon = "vaadin:upload", title = "Hydraulic Station Data Import")
@PermitAll
public class HydraulicStationDataImportView extends Main {

    private final HydraulicStationDataService hydraulicStationDataService;

    public HydraulicStationDataImportView(HydraulicStationDataService hydraulicStationDataService) {
        this.hydraulicStationDataService = hydraulicStationDataService;

        H2 title = new H2("Hydraulic Station Data Import");
        Paragraph description = new Paragraph("Laden Sie die CSV-Datei (energy_data_2025_HydraulicStation.csv) hoch.");

        MemoryBuffer buffer = new MemoryBuffer();
        Upload upload = new Upload(buffer);
        upload.setAcceptedFileTypes(".csv");
        upload.addSucceededListener(event -> {
            try {
                processFile(buffer.getInputStream());
            } catch (Exception e) {
                Notification.show("Fehler beim Verarbeiten der Datei: " + e.getMessage(), 5000, Notification.Position.MIDDLE)
                        .addThemeVariants(NotificationVariant.LUMO_ERROR);
            }
        });

        VerticalLayout layout = new VerticalLayout(title, description, upload);
        add(layout);
    }

    private void processFile(InputStream inputStream) throws Exception {
        List<HydraulicStationData> dataList = new ArrayList<>();
        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

        try (BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream))) {
            String line;
            boolean isFirstLine = true;
            while ((line = reader.readLine()) != null) {
                if (line.trim().isEmpty() || line.startsWith("#")) {
                    continue;
                }
                if (isFirstLine) {
                    if (line.toLowerCase().contains("datetime")) {
                        isFirstLine = false;
                        continue;
                    }
                    isFirstLine = false;
                }

                String[] parts = line.split(";");
                if (parts.length >= 3) {
                    HydraulicStationData data = new HydraulicStationData();
                    data.setDateTime(LocalDateTime.parse(parts[0], formatter));
                    data.setConsumedElectricalEnergyHeating(Double.parseDouble(parts[1]));
                    data.setHeatGeneratedHeating(Double.parseDouble(parts[2]));
                    dataList.add(data);
                }
            }
        }

        ImportResult result = hydraulicStationDataService.importData(dataList);
        Notification.show("Import abgeschlossen. Importiert: " + result.imported() + ", Ignoriert: " + result.ignored(),
                5000, Notification.Position.MIDDLE)
                .addThemeVariants(NotificationVariant.LUMO_SUCCESS);
    }
}
