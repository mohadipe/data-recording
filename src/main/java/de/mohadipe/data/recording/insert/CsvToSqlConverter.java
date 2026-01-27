package de.mohadipe.data.recording.insert;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class CsvToSqlConverter {

    private static final String INPUT_FILENAME = "system_data_2025.csv";
    private static final String OUTPUT_FILENAME = "system_data.sql";
    private static final int BATCH_SIZE = 100;
    private static final String TABLE_NAME = "system_data";

    public static void main(String[] args) {
        System.out.println("Starte Konvertierung...");

        try (BufferedReader reader = Files.newBufferedReader(Paths.get(INPUT_FILENAME), StandardCharsets.UTF_8);
             BufferedWriter writer = Files.newBufferedWriter(Paths.get(OUTPUT_FILENAME), StandardCharsets.UTF_8)) {

            // 1. Metadaten-Zeile überspringen (Zeile 0 im Python-Skript)
            reader.readLine();

            // 2. Header lesen (Zeile 1 im Python-Skript)
            String headerLine = reader.readLine();
            if (headerLine == null) {
                throw new IOException("Die CSV-Datei scheint leer zu sein oder hat keinen Header.");
            }

            // Spalten bereinigen
            String[] rawColumns = headerLine.split(";");
            List<String> columns = new ArrayList<>();
            for (String col : rawColumns) {
                columns.add(cleanColName(col));
            }

            // 3. SQL Header schreiben
            writer.write("USE verbrauch;");
            writer.newLine();
            writer.newLine();
            
            writer.write("CREATE TABLE IF NOT EXISTS " + TABLE_NAME + " (");
            writer.newLine();
            writer.write("    id INT AUTO_INCREMENT PRIMARY KEY,");
            writer.newLine();
            writer.write("    date_time DATETIME,");
            writer.newLine();
            writer.write("    outdoor_temperature DOUBLE");
            writer.newLine();
            writer.write(");");
            writer.newLine();
            writer.newLine();

            // 4. Daten verarbeiten und Inserts generieren
            String line;
            List<String> batchValues = new ArrayList<>();
            String columnsString = String.join(", ", columns);

            while ((line = reader.readLine()) != null) {
                if (line.trim().isEmpty()) continue;

                String[] values = line.split(";");
                List<String> formattedValues = new ArrayList<>();

                for (int i = 0; i < columns.size(); i++) {
                    String colName = columns.get(i);
                    String val = (i < values.length) ? values[i] : ""; // Sicherheit falls Wert fehlt

                    if (colName.equals("date_time")) {
                        formattedValues.add("'" + val + "'");
                    } else {
                        // Zahlen so übernehmen (Java/SQL nutzen Punkt als Dezimaltrenner, passt zur CSV)
                        formattedValues.add(val);
                    }
                }

                batchValues.add("(" + String.join(", ", formattedValues) + ")");

                // Wenn Batch voll ist, schreiben
                if (batchValues.size() >= BATCH_SIZE) {
                    writeInsertBlock(writer, columnsString, batchValues);
                    batchValues.clear();
                }
            }

            // Verbleibende Zeilen schreiben
            if (!batchValues.isEmpty()) {
                writeInsertBlock(writer, columnsString, batchValues);
            }

            System.out.println("Datei '" + OUTPUT_FILENAME + "' wurde erfolgreich erstellt!");

        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    // Hilfsmethode zum Schreiben eines Insert-Blocks
    private static void writeInsertBlock(BufferedWriter writer, String columns, List<String> values) throws IOException {
        writer.write("INSERT INTO " + TABLE_NAME + " (" + columns + ")");
        writer.newLine();
        writer.write("VALUES");
        writer.newLine();
        
        for (int i = 0; i < values.size(); i++) {
            writer.write("    " + values.get(i));
            if (i < values.size() - 1) {
                writer.write(",");
            } else {
                writer.write(";");
            }
            writer.newLine();
        }
        writer.newLine();
    }

    // Hilfsmethode: CamelCase zu snake_case und Bereinigung
    private static String cleanColName(String col) {
        col = col.replace(":", "_");
        // Regex Lookaround Ersatz: Finde Großbuchstaben, die nicht am Anfang stehen
        Matcher m = Pattern.compile("(?<!^)(?=[A-Z])").matcher(col);
        col = m.replaceAll("_").toLowerCase();
        return col;
    }
}