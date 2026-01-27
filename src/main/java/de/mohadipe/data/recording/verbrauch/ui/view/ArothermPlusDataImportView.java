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
import de.mohadipe.data.recording.verbrauch.domain.ArothermPlusData;
import de.mohadipe.data.recording.verbrauch.service.ArothermPlusDataService;
import de.mohadipe.data.recording.verbrauch.service.ImportResult;
import jakarta.annotation.security.PermitAll;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

@Route("arotherm-plus-data-import")
@PageTitle("Arotherm Plus Data Import")
@Menu(order = 2, icon = "vaadin:upload", title = "Arotherm Plus Data Import")
@PermitAll
public class ArothermPlusDataImportView extends Main {

    private final ArothermPlusDataService arothermPlusDataService;

    public ArothermPlusDataImportView(ArothermPlusDataService arothermPlusDataService) {
        this.arothermPlusDataService = arothermPlusDataService;

        H2 title = new H2("Arotherm Plus Data Import");
        Paragraph description = new Paragraph("Laden Sie die CSV-Datei (energy_data_2025_ArothermPlus.csv) hoch.");

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
        List<ArothermPlusData> dataList = new ArrayList<>();
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
                if (parts.length >= 7) {
                    ArothermPlusData data = new ArothermPlusData();
                    data.setDateTime(LocalDateTime.parse(parts[0], formatter));
                    data.setConsumedElectricalEnergyHeating(Double.parseDouble(parts[1]));
                    data.setConsumedElectricalEnergyDomesticHotWater(Double.parseDouble(parts[2]));
                    data.setHeatGeneratedHeating(Double.parseDouble(parts[3]));
                    data.setHeatGeneratedDomesticHotWater(Double.parseDouble(parts[4]));
                    data.setEarnedEnvironmentEnergyHeating(Double.parseDouble(parts[5]));
                    data.setEarnedEnvironmentEnergyDomesticHotWater(Double.parseDouble(parts[6]));
                    dataList.add(data);
                }
            }
        }

        ImportResult result = arothermPlusDataService.importData(dataList);
        Notification.show("Import abgeschlossen. Importiert: " + result.imported() + ", Ignoriert: " + result.ignored(),
                5000, Notification.Position.MIDDLE)
                .addThemeVariants(NotificationVariant.LUMO_SUCCESS);
    }
}
