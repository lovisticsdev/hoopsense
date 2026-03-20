package com.lovistics.hoopsense

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.lovistics.hoopsense.ui.navigation.MainScreen
import com.lovistics.hoopsense.ui.theme.HoopSenseTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            HoopSenseTheme {
                MainScreen()
            }
        }
    }
}