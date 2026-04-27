#include <QApplication>
#include <QWidget>
#include <QPushButton>
#include <QLineEdit>
#include <QVBoxLayout>
#include <QProcess>
#include <QLabel>

class MyWindow : public QWidget {
public:
    MyWindow() {
        // Layout principal
        QVBoxLayout* layout = new QVBoxLayout(this);

        // Champ de texte
        inputText = new QLineEdit(this);
        inputText->setPlaceholderText("Enter text...");
        layout->addWidget(inputText);

        // Bouton "OK"
        QPushButton* button = new QPushButton("OK", this);
        layout->addWidget(button);

        // Connecter le bouton à l'action
        connect(button, &QPushButton::clicked, this, &MyWindow::onButtonClicked);

        // Ajouter un label de confirmation
        outputLabel = new QLabel("", this);
        layout->addWidget(outputLabel);

        setLayout(layout);
        setWindowTitle("Text Command Interface");
        resize(400, 200);
    }

private:
    QLineEdit* inputText;
    QLabel* outputLabel;

    void onButtonClicked() {
        QString text = inputText->text();
        if (!text.isEmpty()) {
            // Exécuter la commande Python avec le texte
            QString command = QString("python3 zorya.py -c '%1'").arg(text);
            QProcess::execute(command);

            // Afficher un message de confirmation
            outputLabel->setText("Command executed with input: " + text);
        } else {
            outputLabel->setText("Please enter some text.");
        }
    }
};

int main(int argc, char *argv[]) {
    QApplication app(argc, argv);

    MyWindow window;
    window.show();

    return app.exec();
}
