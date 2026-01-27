package de.mohadipe.data.recording.wertpapiere.ui.view;

import com.vaadin.flow.component.button.Button;
import com.vaadin.flow.component.button.ButtonVariant;
import com.vaadin.flow.component.datepicker.DatePicker;
import com.vaadin.flow.component.grid.Grid;
import com.vaadin.flow.component.html.Main;
import com.vaadin.flow.component.html.Span;
import com.vaadin.flow.component.notification.Notification;
import com.vaadin.flow.component.notification.NotificationVariant;
import com.vaadin.flow.component.select.Select;
import com.vaadin.flow.component.textfield.NumberField;
import com.vaadin.flow.router.Menu;
import com.vaadin.flow.router.PageTitle;
import com.vaadin.flow.router.Route;
import com.vaadin.flow.theme.lumo.LumoUtility;
import de.mohadipe.data.recording.base.ui.component.ViewToolbar;
import de.mohadipe.data.recording.wertpapiere.domain.Etf;
import de.mohadipe.data.recording.wertpapiere.domain.WknInvestDatum;
import de.mohadipe.data.recording.wertpapiere.service.EtfService;
import de.mohadipe.data.recording.wertpapiere.service.WknInvestDatumService;
import de.mohadipe.data.recording.wertpapiere.view.model.WknInvestDatumDTO;
import jakarta.annotation.security.PermitAll;
import org.springframework.data.domain.Pageable;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalDate;
import java.util.Locale;

import static com.vaadin.flow.spring.data.VaadinSpringDataHelpers.toSpringPageRequest;

@Route("wkn-invest-datum-list")
@PageTitle("Wkn Invest Datum List")
@Menu(order = 0, icon = "vaadin:money-deposit", title = "Wkn Invest Datum List")
@PermitAll // When security is enabled, allow all authenticated users
public class WknInvestDatumListView extends Main {

    private final WknInvestDatumService wknInvestDatumService;

    final Select<Etf> select;
    final Button createBtn;
    final Grid<WknInvestDatumDTO> taskGrid;
    final DatePicker investDatum;
    final NumberField betrag;

    public WknInvestDatumListView(WknInvestDatumService wknInvestDatumService, EtfService etfService, Clock clock) {
        this.wknInvestDatumService = wknInvestDatumService;

        select = new Select<>();
        select.setLabel("Invest for Wkn");
        select.setItems(etfService.list(Pageable.unpaged())); // Lädt alle ETFs
        select.setItemLabelGenerator(Etf::getWkn);

        // datum
        investDatum = new DatePicker("Invest Datum");
        investDatum.setValue(LocalDate.now(clock));
        investDatum.setRequired(true);
        investDatum.setLocale(Locale.GERMAN);

        // invest betrag
        betrag = new NumberField("Betrag (€)");
        betrag.setValue(0.0);
        betrag.setMin(0.01);
        betrag.setStep(0.01);
        betrag.setPrefixComponent(new Span("€"));
        betrag.setRequired(true);
        betrag.setHelperText("Bitte geben Sie den Investitionsbetrag ein (mindestens 0,01 €)");

        createBtn = new Button("Create", event -> createWknInvest());
        createBtn.addThemeVariants(ButtonVariant.LUMO_PRIMARY);

        taskGrid = new Grid<>();
        taskGrid.setItems(query -> wknInvestDatumService.listAsDTO(toSpringPageRequest(query)).stream());
        taskGrid.addColumn(WknInvestDatumDTO::wknNummer).setHeader("WKN").setSortable(true).setSortProperty("wkn.wkn");
        taskGrid.addColumn(WknInvestDatumDTO::datum).setHeader("Datum").setSortable(true).setSortProperty("datum");
        taskGrid.addColumn(WknInvestDatumDTO::invest).setHeader("Invest").setSortable(true).setSortProperty("invest");
        taskGrid.setSizeFull();

        select.addValueChangeListener(event -> {
            Etf selectedEtf = event.getValue();
            updateGrid(selectedEtf.getId());
        });

        setSizeFull();
        addClassNames(LumoUtility.BoxSizing.BORDER, LumoUtility.Display.FLEX, LumoUtility.FlexDirection.COLUMN,
                LumoUtility.Padding.MEDIUM, LumoUtility.Gap.SMALL);


        add(new ViewToolbar("Invests for Etf", ViewToolbar.group(select, investDatum, betrag, createBtn)));

        add(taskGrid);
    }

    private void updateGrid(Long wkn) {
        taskGrid.setItems(query ->
                wknInvestDatumService.listByWknAsDTO(wkn, toSpringPageRequest(query)).stream()
        );
    }

    private void createWknInvest() {
        Etf selectedEtf = select.getValue();
        WknInvestDatum wknInvestDatum = new WknInvestDatum();
        wknInvestDatum.setWkn(selectedEtf);
        wknInvestDatum.setInvest(BigDecimal.valueOf(betrag.getValue()));
        wknInvestDatum.setDatum(investDatum.getValue());

        wknInvestDatumService.createWknInvest(wknInvestDatum);
        updateGrid(selectedEtf.getId());

        betrag.setValue(0.0);
        Notification.show("Investition hinzugefügt", 3000, Notification.Position.BOTTOM_END)
                .addThemeVariants(NotificationVariant.LUMO_SUCCESS);
    }

}
